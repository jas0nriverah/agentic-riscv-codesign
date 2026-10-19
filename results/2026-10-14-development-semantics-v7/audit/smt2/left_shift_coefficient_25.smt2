(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x270 (bvmul x (_ bv33554432 32))))
(let ((?x268 (bvshl x (_ bv25 32))))
(and (distinct ?x268 ?x270) true))))
(check-sat)
