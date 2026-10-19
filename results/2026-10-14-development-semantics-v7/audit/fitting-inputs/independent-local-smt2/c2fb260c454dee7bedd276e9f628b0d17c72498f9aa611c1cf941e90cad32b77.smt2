(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x703 (bvadd (bvshl independent_opaque_1 (bvand (_ bv7 32) (_ bv31 32))) (bvsub (_ bv0 32) (bvshl independent_opaque_2 (bvand (_ bv7 32) (_ bv31 32)))))))
(let ((?x756 (bvadd independent_opaque_0 ?x703)))
(let ((?x33 (bvand (_ bv7 32) (_ bv31 32))))
(let ((?x98 (bvadd independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x33))))
(and (distinct ?x98 ?x756) true))))))
(check-sat)
