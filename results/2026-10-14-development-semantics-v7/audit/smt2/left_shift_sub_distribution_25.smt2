(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x272 (bvshl y (_ bv25 32))))
(let ((?x268 (bvshl x (_ bv25 32))))
(let ((?x275 (bvsub ?x268 ?x272)))
(let ((?x24 (bvsub x y)))
(let ((?x274 (bvshl ?x24 (_ bv25 32))))
(and (distinct ?x274 ?x275) true)))))))
(check-sat)
