(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x236 (bvshl y (_ bv21 32))))
(let ((?x232 (bvshl x (_ bv21 32))))
(let ((?x237 (bvadd ?x232 ?x236)))
(let ((?x19 (bvadd x y)))
(let ((?x235 (bvshl ?x19 (_ bv21 32))))
(and (distinct ?x235 ?x237) true)))))))
(check-sat)
