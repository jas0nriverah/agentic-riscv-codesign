(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x326 (bvshl y (_ bv31 32))))
(let ((?x322 (bvshl x (_ bv31 32))))
(let ((?x329 (bvsub ?x322 ?x326)))
(let ((?x24 (bvsub x y)))
(let ((?x328 (bvshl ?x24 (_ bv31 32))))
(and (distinct ?x328 ?x329) true)))))))
(check-sat)
