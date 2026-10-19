(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x308 (bvshl y (_ bv29 32))))
(let ((?x304 (bvshl x (_ bv29 32))))
(let ((?x309 (bvadd ?x304 ?x308)))
(let ((?x19 (bvadd x y)))
(let ((?x307 (bvshl ?x19 (_ bv29 32))))
(and (distinct ?x307 ?x309) true)))))))
(check-sat)
