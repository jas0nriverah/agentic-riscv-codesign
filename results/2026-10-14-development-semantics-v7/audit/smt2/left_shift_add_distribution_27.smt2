(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x290 (bvshl y (_ bv27 32))))
(let ((?x286 (bvshl x (_ bv27 32))))
(let ((?x291 (bvadd ?x286 ?x290)))
(let ((?x19 (bvadd x y)))
(let ((?x289 (bvshl ?x19 (_ bv27 32))))
(and (distinct ?x289 ?x291) true)))))))
(check-sat)
