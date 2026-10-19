(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x290 (bvshl y (_ bv27 32))))
(let ((?x286 (bvshl x (_ bv27 32))))
(let ((?x293 (bvsub ?x286 ?x290)))
(let ((?x24 (bvsub x y)))
(let ((?x292 (bvshl ?x24 (_ bv27 32))))
(and (distinct ?x292 ?x293) true)))))))
(check-sat)
